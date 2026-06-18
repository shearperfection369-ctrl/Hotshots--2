import React, { useEffect, useState, useCallback, useMemo } from "react";
import Topbar from "@/components/Topbar";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import {
  AlertTriangle, Clock, MapPin, AlertOctagon, FileText, TrendingDown,
  PhoneOff, Compass, Sparkles, Moon, RefreshCw, Send, Copy, CheckCircle2,
  Loader2, Bell, Activity, Plus, ShieldAlert,
} from "lucide-react";
import { toast } from "sonner";

/**
 * /triage — Orisei AI Shipment Triage & Exception Console.
 *
 * Identifies late, lost, off-route, no-GPS, missing-POD, margin-drift and
 * unresponsive-carrier exceptions in real time. AI co-pilot drafts the
 * customer note + carrier escalation script per exception. After-hours
 * routing flips on between 6pm–7am UTC.
 */

const ICONS = {
  pickup_late: Clock, delivery_late: AlertTriangle, no_gps_checkin: MapPin,
  lost_load: AlertOctagon, pod_missing: FileText, margin_drift: TrendingDown,
  carrier_no_response: PhoneOff, off_route: Compass,
};

const SEVERITY = {
  critical: { color: "text-red-300",     bg: "bg-red-950/40",     border: "border-red-400/50",   pill: "bg-red-500/20 text-red-200 border-red-400/50", glow: "shadow-[0_0_30px_rgba(239,68,68,0.45)]" },
  high:     { color: "text-amber-300",   bg: "bg-amber-950/30",   border: "border-amber-400/50", pill: "bg-amber-500/20 text-amber-200 border-amber-400/50" },
  medium:   { color: "text-cyan-300",    bg: "bg-cyan-950/30",    border: "border-cyan-400/40",  pill: "bg-cyan-500/20 text-cyan-200 border-cyan-400/40" },
  low:      { color: "text-slate-300",   bg: "bg-slate-900/60",   border: "border-white/10",     pill: "bg-slate-500/20 text-slate-300 border-white/20" },
};

export default function ShipmentTriage() {
  const [dash, setDash] = useState(null);
  const [items, setItems] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [filter, setFilter] = useState("active");
  const [open, setOpen] = useState(null);
  const [polishing, setPolishing] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);
  const [manualDraft, setManualDraft] = useState({
    booked_id: "", exception_type: "pickup_late", severity: "medium",
    signal: "", notes: "",
  });

  const load = useCallback(async () => {
    try {
      const [d, l, bk] = await Promise.all([
        api.get("/shipment-triage/dashboard"),
        api.get("/shipment-triage/exceptions"),
        api.get("/brokerage/margins").catch(() => ({ data: { bookings: [] } })),
      ]);
      setDash(d.data); setItems(l.data.items || []);
      setBookings((bk.data?.bookings || []).filter(b => b.booked_id));
    } catch (e) { toast.error("Could not load triage data"); }
  }, []);

  const scan = useCallback(async () => {
    setScanning(true);
    try {
      const { data } = await api.post("/shipment-triage/scan");
      if (data.created_count > 0)
        toast.warning(`${data.created_count} new exception${data.created_count > 1 ? "s" : ""} detected`);
      else
        toast.success("All clear · no new exceptions");
      await load();
    } catch (e) { toast.error("Scan failed"); }
    finally { setScanning(false); }
  }, [load]);

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);  // auto-refresh every 30s
    return () => clearInterval(t);
  }, [load]);

  const filtered = useMemo(() => {
    if (filter === "all") return items;
    if (filter === "active")
      return items.filter(i => ["open","acknowledged","in_progress"].includes(i.status));
    return items.filter(i => i.status === filter);
  }, [items, filter]);

  const setStatus = async (ex, status, resolution_notes) => {
    try {
      await api.post(`/shipment-triage/exceptions/${ex.exception_id}/status`,
        { status, resolution_notes });
      toast.success(`Marked ${status}`);
      load();
      if (open?.exception_id === ex.exception_id) setOpen({ ...open, status });
    } catch (e) { toast.error("Could not update"); }
  };

  const polish = async () => {
    if (!open) return;
    setPolishing(true);
    try {
      const { data } = await api.post(`/shipment-triage/exceptions/${open.exception_id}/ai-polish`);
      setOpen({ ...open, advice_ai_polished: data.advice_ai_polished, ai_polished: data.ai_polished });
      if (data.ai_polished) toast.success("AI polish complete");
      else toast.info("AI unavailable · showing deterministic playbook");
    } catch (e) { toast.error("AI polish failed"); }
    finally { setPolishing(false); }
  };

  const createManual = async () => {
    if (!manualDraft.booked_id) { toast.error("Pick a booking"); return; }
    try {
      await api.post("/shipment-triage/exceptions", manualDraft);
      toast.success("Exception reported");
      setManualOpen(false);
      setManualDraft({ ...manualDraft, signal: "", notes: "" });
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not save"); }
  };

  return (
    <>
      <Topbar
        title="AI Triage · Exception Console"
        subtitle={`Live anomaly detection · ${dash?.active_count ?? "..."} active · ${dash?.is_after_hours ? "AFTER HOURS" : "BUSINESS HOURS"}`}
      />
      <div className="p-4 md:p-6 grid grid-cols-12 gap-4">

        {/* Top status band */}
        <Card className={`col-span-12 p-5 border-2 ${dash?.critical_count > 0 ? "border-red-400/60 shadow-[0_0_30px_rgba(239,68,68,0.35)]" : dash?.high_count > 0 ? "border-amber-400/50" : "border-emerald-400/40"} bg-gradient-to-r from-slate-950 via-slate-900 to-slate-950 relative overflow-hidden`}
              data-testid="triage-band">
          <div className="pointer-events-none absolute inset-0 opacity-[0.06]"
               style={{ backgroundImage: "linear-gradient(rgba(239,68,68,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(239,68,68,0.5) 1px, transparent 1px)", backgroundSize: "40px 40px" }} />
          <div className="relative z-10 grid grid-cols-12 gap-4 items-center">
            <div className="col-span-12 md:col-span-3">
              <div className="text-[10px] uppercase tracking-[0.3em] text-red-300 font-mono">Active Exceptions</div>
              <div className="text-5xl font-mono text-white mt-1 tabular-nums" data-testid="active-count">
                {dash?.active_count ?? "—"}
              </div>
              <div className="flex gap-3 mt-2 text-xs">
                {dash?.critical_count > 0 && (
                  <Badge className={SEVERITY.critical.pill}>{dash.critical_count} CRITICAL</Badge>
                )}
                {dash?.high_count > 0 && (
                  <Badge className={SEVERITY.high.pill}>{dash.high_count} HIGH</Badge>
                )}
                {!dash?.critical_count && !dash?.high_count && (
                  <Badge className="bg-emerald-500/20 text-emerald-200 border-emerald-400/40">All clear</Badge>
                )}
              </div>
            </div>
            <div className="col-span-12 md:col-span-3">
              <div className="text-[10px] uppercase tracking-widest text-slate-400 font-mono">Resolved Total</div>
              <div className="text-2xl font-mono text-emerald-300 mt-1">{dash?.resolved_total ?? 0}</div>
              <div className="text-[11px] text-slate-400">MTTR {dash?.mttr_hours ? `${dash.mttr_hours}h` : "—"}</div>
            </div>
            <div className="col-span-12 md:col-span-3">
              <div className="text-[10px] uppercase tracking-widest text-slate-400 font-mono">Mode</div>
              <div className="flex items-center gap-2 mt-1">
                {dash?.is_after_hours ? (
                  <Badge className="bg-indigo-500/20 text-indigo-200 border-indigo-400/40 text-sm py-1">
                    <Moon size={12} className="mr-1" /> AFTER HOURS
                  </Badge>
                ) : (
                  <Badge className="bg-emerald-500/20 text-emerald-200 border-emerald-400/40 text-sm py-1">
                    <Activity size={12} className="mr-1" /> BUSINESS
                  </Badge>
                )}
              </div>
              <div className="text-[11px] text-slate-400 mt-1">
                High+ severity pages on-call after 6pm UTC
              </div>
            </div>
            <div className="col-span-12 md:col-span-3 flex gap-2 justify-end">
              <Button onClick={() => setManualOpen(true)} variant="outline"
                      data-testid="report-btn"
                      className="bg-slate-900 border-white/10 text-xs">
                <Plus size={12} className="mr-1" /> Report
              </Button>
              <Button onClick={scan} disabled={scanning} data-testid="scan-btn"
                      className="bg-red-500 text-white hover:bg-red-400 font-semibold">
                {scanning ? <Loader2 className="animate-spin mr-1.5" size={14} /> : <RefreshCw className="mr-1.5" size={14} />}
                Scan now
              </Button>
            </div>
          </div>
        </Card>

        {/* Filter chips */}
        <div className="col-span-12 flex gap-2 flex-wrap" data-testid="triage-filters">
          {["active", "open", "acknowledged", "in_progress", "resolved", "all"].map(f => (
            <button key={f}
                    data-testid={`filter-${f}`}
                    onClick={() => setFilter(f)}
                    className={`px-3 py-1.5 rounded-md text-xs font-mono uppercase tracking-wider transition border ${
                      filter === f
                        ? "bg-red-500 text-white border-red-400"
                        : "border-white/10 text-slate-400 hover:border-red-400/40"
                    }`}>
              {f.replace("_", " ")}
            </button>
          ))}
        </div>

        {/* Exception list */}
        <div className="col-span-12 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {filtered.map(ex => {
            const Icon = ICONS[ex.exception_type] || AlertTriangle;
            const sev = SEVERITY[ex.severity] || SEVERITY.medium;
            return (
              <Card key={ex.exception_id}
                    data-testid={`ex-${ex.exception_id}`}
                    onClick={() => setOpen(ex)}
                    className={`p-4 cursor-pointer transition border-2 ${sev.border} ${sev.bg} hover:scale-[1.01] ${sev.glow || ""}`}>
                <div className="flex items-start gap-3">
                  <div className={`flex-none w-10 h-10 rounded-lg grid place-items-center ${sev.bg} border ${sev.border} ${sev.color}`}>
                    <Icon size={18} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <div className="text-sm font-semibold text-white">{ex.advice?.title || ex.exception_type}</div>
                      <Badge className={`${sev.pill} text-[9px]`}>{ex.severity.toUpperCase()}</Badge>
                    </div>
                    <div className="font-mono text-[11px] text-cyan-200 mt-0.5">{ex.booked_id}</div>
                    <div className="text-[11px] text-slate-300 truncate mt-0.5">
                      {ex.origin} → {ex.destination}
                    </div>
                    <div className="text-[10px] text-slate-400 truncate mt-1 italic">
                      {ex.signal}
                    </div>
                  </div>
                </div>
                <div className="flex justify-between items-center mt-3 pt-2 border-t border-white/5">
                  <Badge variant="outline" className="border-white/10 text-slate-400 text-[9px]">
                    {ex.status?.toUpperCase()}
                  </Badge>
                  <div className="text-[10px] text-slate-500 font-mono">
                    {new Date(ex.created_at).toLocaleString()}
                  </div>
                </div>
              </Card>
            );
          })}
          {!filtered.length && (
            <Card className="col-span-full p-10 bg-slate-950/60 border-white/10 text-center text-slate-500 text-sm">
              {filter === "active" ? "🎯 All clear — no active exceptions." : `No exceptions in "${filter}" state.`}
            </Card>
          )}
        </div>
      </div>

      {/* Detail / triage modal */}
      <Dialog open={!!open} onOpenChange={() => setOpen(null)}>
        <DialogContent className="bg-slate-950 border-red-400/40 text-white max-w-3xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-3">
              {open && (() => {
                const Icon = ICONS[open.exception_type] || AlertTriangle;
                const sev = SEVERITY[open.severity];
                return (
                  <>
                    <div className={`w-10 h-10 rounded-lg grid place-items-center ${sev.bg} border ${sev.border} ${sev.color}`}>
                      <Icon size={20} />
                    </div>
                    <div>
                      <div className="text-lg">{open.advice?.title}</div>
                      <div className="text-xs text-slate-400 font-mono mt-0.5">
                        {open.booked_id} · {open.origin} → {open.destination}
                      </div>
                    </div>
                    <Badge className={`${sev.pill} ml-auto`}>{open.severity.toUpperCase()}</Badge>
                  </>
                );
              })()}
            </DialogTitle>
            <DialogDescription className="text-slate-400 text-xs pt-2">
              {open?.signal} · Detected {open?.created_at && new Date(open.created_at).toLocaleString()}
            </DialogDescription>
          </DialogHeader>

          {open && (
            <div className="space-y-3">
              {/* Escalation banner */}
              <Card className={`p-3 ${open.advice?.after_hours ? "bg-indigo-950/40 border-indigo-400/40" : "bg-amber-950/30 border-amber-400/30"}`}>
                <div className="flex items-center gap-2">
                  {open.advice?.after_hours ? <Moon size={14} className="text-indigo-300" /> : <Bell size={14} className="text-amber-300" />}
                  <span className="text-xs font-semibold text-white">{open.advice?.escalation}</span>
                </div>
              </Card>

              {/* Root cause */}
              <div>
                <div className="text-[10px] uppercase tracking-widest text-cyan-300 font-mono mb-1">AI Root Cause</div>
                <div className="text-sm text-slate-200 italic" data-testid="root-cause">
                  {open.advice?.root_cause}
                </div>
              </div>

              {/* Playbook */}
              <div>
                <div className="text-[10px] uppercase tracking-widest text-cyan-300 font-mono mb-2">3-Step Playbook</div>
                <ol className="space-y-1.5">
                  {(open.advice?.playbook || []).map((p, i) => (
                    <li key={i} className="flex gap-2 text-sm text-slate-200">
                      <span className="flex-none w-5 h-5 rounded-full bg-red-500/20 border border-red-400/40 text-red-300 grid place-items-center text-[10px] font-mono">{i + 1}</span>
                      <span>{p}</span>
                    </li>
                  ))}
                </ol>
              </div>

              {/* Customer + Carrier messages */}
              <div className="grid grid-cols-2 gap-3">
                <Card className="p-3 bg-cyan-950/30 border-cyan-400/30">
                  <div className="flex justify-between items-center mb-1">
                    <div className="text-[10px] uppercase tracking-widest text-cyan-300 font-mono">Customer message</div>
                    <Button size="sm" variant="outline"
                            onClick={() => { navigator.clipboard.writeText(open.advice.customer_message); toast.success("Copied"); }}
                            className="bg-slate-900 border-white/10 h-6 text-[10px]">
                      <Copy size={10} className="mr-1" /> Copy
                    </Button>
                  </div>
                  <div className="text-xs text-slate-200 whitespace-pre-wrap" data-testid="customer-msg">
                    {open.advice?.customer_message}
                  </div>
                </Card>
                <Card className="p-3 bg-red-950/30 border-red-400/30">
                  <div className="flex justify-between items-center mb-1">
                    <div className="text-[10px] uppercase tracking-widest text-red-300 font-mono">Carrier escalation</div>
                    <Button size="sm" variant="outline"
                            onClick={() => { navigator.clipboard.writeText(open.advice.carrier_message); toast.success("Copied"); }}
                            className="bg-slate-900 border-white/10 h-6 text-[10px]">
                      <Copy size={10} className="mr-1" /> Copy
                    </Button>
                  </div>
                  <div className="text-xs text-slate-200 whitespace-pre-wrap" data-testid="carrier-msg">
                    {open.advice?.carrier_message}
                  </div>
                </Card>
              </div>

              {/* AI polished */}
              {open.advice_ai_polished && (
                <Card className="p-3 bg-amber-950/30 border-amber-400/40">
                  <div className="flex items-center gap-2 mb-1">
                    <Sparkles size={12} className="text-amber-300" />
                    <div className="text-[10px] uppercase tracking-widest text-amber-300 font-mono">
                      Claude Sonnet polish
                    </div>
                  </div>
                  <div className="text-xs text-slate-200 whitespace-pre-wrap font-mono" data-testid="ai-polished">
                    {open.advice_ai_polished}
                  </div>
                </Card>
              )}
            </div>
          )}

          <DialogFooter className="flex-wrap gap-2">
            <Button onClick={polish} disabled={polishing} variant="outline"
                    data-testid="polish-btn"
                    className="bg-slate-900 border-amber-400/40 text-amber-200">
              {polishing ? <Loader2 className="animate-spin mr-1.5" size={12} /> : <Sparkles size={12} className="mr-1.5" />}
              AI Polish
            </Button>
            {open && open.status !== "in_progress" && (
              <Button onClick={() => setStatus(open, "in_progress")}
                      data-testid="ack-btn"
                      className="bg-cyan-500 text-black hover:bg-cyan-400">
                <ShieldAlert size={12} className="mr-1.5" /> I&apos;m on it
              </Button>
            )}
            {open && open.status !== "escalated" && open.severity !== "low" && (
              <Button onClick={() => setStatus(open, "escalated")}
                      data-testid="esc-btn"
                      variant="outline"
                      className="bg-red-950/40 border-red-400/40 text-red-200">
                Escalate
              </Button>
            )}
            {open && open.status !== "resolved" && (
              <Button onClick={() => {
                        const notes = window.prompt("Resolution notes (optional):");
                        setStatus(open, "resolved", notes || undefined);
                        setOpen(null);
                      }}
                      data-testid="resolve-btn"
                      className="bg-emerald-500 text-black hover:bg-emerald-400">
                <CheckCircle2 size={12} className="mr-1.5" /> Resolve
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Manual report modal */}
      <Dialog open={manualOpen} onOpenChange={setManualOpen}>
        <DialogContent className="bg-slate-950 border-white/10 text-white max-w-md">
          <DialogHeader>
            <DialogTitle>Report exception manually</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-[10px] uppercase tracking-widest text-slate-400">Booking</Label>
              <select value={manualDraft.booked_id}
                      data-testid="manual-booking"
                      onChange={(e) => setManualDraft({ ...manualDraft, booked_id: e.target.value })}
                      className="w-full bg-slate-900 border border-white/10 rounded px-3 py-2 text-sm">
                <option value="">— pick a booking —</option>
                {bookings.map(b => (
                  <option key={b.booked_id} value={b.booked_id}>
                    {b.booked_id} · {b.origin} → {b.destination}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label className="text-[10px] uppercase tracking-widest text-slate-400">Type</Label>
                <select value={manualDraft.exception_type}
                        onChange={(e) => setManualDraft({ ...manualDraft, exception_type: e.target.value })}
                        className="w-full bg-slate-900 border border-white/10 rounded px-3 py-2 text-sm">
                  {Object.keys(ICONS).map(k => (
                    <option key={k} value={k}>{k.replace("_", " ")}</option>
                  ))}
                </select>
              </div>
              <div>
                <Label className="text-[10px] uppercase tracking-widest text-slate-400">Severity</Label>
                <select value={manualDraft.severity}
                        onChange={(e) => setManualDraft({ ...manualDraft, severity: e.target.value })}
                        className="w-full bg-slate-900 border border-white/10 rounded px-3 py-2 text-sm">
                  <option value="low">low</option><option value="medium">medium</option>
                  <option value="high">high</option><option value="critical">critical</option>
                </select>
              </div>
            </div>
            <div>
              <Label className="text-[10px] uppercase tracking-widest text-slate-400">Signal / observation</Label>
              <Input value={manualDraft.signal}
                     onChange={(e) => setManualDraft({ ...manualDraft, signal: e.target.value })}
                     placeholder="Driver phone off · last GPS 7h ago"
                     className="bg-slate-900 border-white/10" />
            </div>
            <div>
              <Label className="text-[10px] uppercase tracking-widest text-slate-400">Notes</Label>
              <Textarea value={manualDraft.notes}
                        onChange={(e) => setManualDraft({ ...manualDraft, notes: e.target.value })}
                        className="bg-slate-900 border-white/10 text-xs min-h-[80px]" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setManualOpen(false)} className="bg-slate-900 border-white/10">Cancel</Button>
            <Button onClick={createManual} data-testid="manual-create-btn" className="bg-red-500 text-white hover:bg-red-400">
              <Send size={14} className="mr-1.5" /> Report
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
