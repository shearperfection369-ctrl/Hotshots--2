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
            {filtered.map(b => (
              <button
                key={b.booked_id}
                data-testid={`workflow-pick-${b.booked_id}`}
                onClick={() => setSelectedId(b.booked_id)}
                className={`w-full text-left p-2.5 rounded-lg border transition-all ${
                  selectedId === b.booked_id
                    ? "bg-cyan-500/10 border-cyan-400/50 shadow-[0_0_15px_rgba(34,211,238,0.25)]"
                    : "bg-slate-900/40 border-white/5 hover:border-cyan-400/30"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="font-mono text-[11px] text-cyan-200">{b.booked_id}</div>
                  <StatusPill status={b.status} />
                </div>
                <div className="text-xs text-white mt-1 truncate">{b.origin} → {b.destination}</div>
                <div className="text-[10px] text-slate-400 mt-0.5 truncate">
                  {b.carrier_name || "Unassigned"} · {b.miles ? `${b.miles}mi` : ""}
                </div>
              </button>
            ))}
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

      {/* Notes modal */}
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
