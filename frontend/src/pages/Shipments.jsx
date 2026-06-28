import React, { useEffect, useMemo, useState } from "react";
import Topbar from "../components/Topbar";
import { api, BACKEND_URL } from "../lib/api";
import { useBrandRefresh } from "../lib/branding";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import {
  Search, AlertTriangle, ExternalLink, ArrowDownToLine, ArrowUpFromLine,
  CheckCircle2, Pencil, XCircle, Mail, Settings2, Upload, FileText, GripVertical
} from "lucide-react";
import { useAuth } from "../lib/auth";

const STATUS_BADGE = {
  in_transit: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
  delayed: "bg-red-500/10 text-red-400 border-red-500/30",
  delivered: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  pending: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
  at_origin: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
  cancelled: "bg-slate-500/10 text-slate-400 border-slate-500/30 line-through",
};

const STATUS_OPTIONS = [
  "pending", "at_origin", "in_transit", "delayed", "delivered", "cancelled",
];

// All columns with default visibility & width — user can customize and persist to localStorage
const DEFAULT_COLUMNS = [
  { id: "done", label: "Done", default: true, width: 50, align: "center" },
  { id: "ship_date", label: "Ship Date", default: true, width: 110 },
  { id: "ship_day", label: "Day", default: true, width: 60 },
  { id: "supplier_origin", label: "Supplier / Origin", default: true, width: 180 },
  { id: "consignee_dest", label: "Consignee / Dest", default: true, width: 180 },
  { id: "carrier", label: "Carrier", default: true, width: 140 },
  { id: "po", label: "PO / Delivery #", default: true, width: 160 },
  { id: "sap_delivery", label: "SAP Delivery #", default: false, width: 140 },
  { id: "skids", label: "Skids", default: true, width: 70, align: "right" },
  { id: "lbs", label: "LBS", default: true, width: 90, align: "right" },
  { id: "dimensions", label: "Dims (L×W×H)", default: false, width: 130 },
  { id: "nmfc", label: "NMFC / Class", default: false, width: 130 },
  { id: "accessorials", label: "Accessorials", default: false, width: 170 },
  { id: "material_controller", label: "Material Controller", default: true, width: 160 },
  { id: "booking", label: "Booking / PRO #", default: true, width: 140 },
  { id: "bid_cost", label: "Bid Cost", default: true, width: 110, align: "right" },
  { id: "hz", label: "HZ", default: true, width: 50, align: "center" },
  { id: "status", label: "Status", default: true, width: 140 },
];

const COLS_STORAGE_KEY = "tms_shipments_cols_v1";
const loadColPrefs = () => {
  try {
    const raw = localStorage.getItem(COLS_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch { return null; }
};
const saveColPrefs = (prefs) => {
  try { localStorage.setItem(COLS_STORAGE_KEY, JSON.stringify(prefs)); } catch {}
};

const MODE_OPTIONS = ["TL", "LTL", "Parcel", "Ocean", "Air", "Rail"];
const DIRECTION_OPTIONS = ["outbound", "inbound"];
const FACILITY_OPTIONS = [
  { id: "", label: "— None —" },
  { id: "GVM", label: "Golden Valley, MN (HQ)" },
  { id: "HOM", label: "Holland, MI" },
  { id: "LVK", label: "Louisville, KY" },
];

const SAP_LINK = (path, params = {}) => {
  const qs = new URLSearchParams({ ...params, ref: path }).toString();
  return `/sap-sync?${qs}`;
};

const SapLink = ({ children, path, params, title, testid }) => (
  <Link
    to={SAP_LINK(path, params)}
    title={title || "Open in SAP S/4HANA"}
    data-testid={testid}
    className="inline-flex items-center gap-1 text-cyan-300 hover:text-cyan-200 hover:underline decoration-cyan-500/40 underline-offset-2"
  >
    {children}
    <ExternalLink size={10} className="opacity-50" />
  </Link>
);

export default function Shipments() {
  const { user } = useAuth();
  const canEdit = user?.role === "admin" || user?.role === "dispatcher";
  const [shipments, setShipments] = useState([]);
  const [direction, setDirection] = useState("ALL");
  const [carrier, setCarrier] = useState("ALL");
  const [mode, setMode] = useState("ALL");
  const [status, setStatus] = useState("ALL");
  const [hazOnly, setHazOnly] = useState(false);
  const [includeCancelled, setIncludeCancelled] = useState(false);
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState(null);
  const [confirmCancel, setConfirmCancel] = useState(null);
  const [emailModal, setEmailModal] = useState(null); // { kind: 'routing'|'carrier', shipment, data }
  const [bolUpload, setBolUpload] = useState(null); // shipment
  const [colCustomizerOpen, setColCustomizerOpen] = useState(false);
  const [cols, setCols] = useState(() => {
    const stored = loadColPrefs();
    if (stored && Array.isArray(stored) && stored.length === DEFAULT_COLUMNS.length) return stored;
    return DEFAULT_COLUMNS.map((c) => ({ id: c.id, visible: c.default, width: c.width }));
  });
  const colMeta = useMemo(() => Object.fromEntries(DEFAULT_COLUMNS.map((c) => [c.id, c])), []);
  const visibleCols = cols.filter((c) => c.visible);
  useEffect(() => { saveColPrefs(cols); }, [cols]);

  // Drag-and-drop reordering of column headers. The cols array order drives
  // render order, so reordering it instantly repositions the column.
  const [dragColId, setDragColId] = useState(null);
  const [overColId, setOverColId] = useState(null);

  const reorderCol = (sourceId, targetId) => {
    if (!sourceId || sourceId === targetId) return;
    setCols((arr) => {
      const next = [...arr];
      const from = next.findIndex((x) => x.id === sourceId);
      const to = next.findIndex((x) => x.id === targetId);
      if (from === -1 || to === -1) return arr;
      const [moved] = next.splice(from, 1);
      next.splice(to, 0, moved);
      return next;
    });
  };

  const load = async () => {
    const { data } = await api.get("/shipments?limit=500");
    setShipments(data);
  };
  useEffect(() => { load(); }, []);
  useBrandRefresh(() => load());

  const carriers = useMemo(() => {
    const set = new Set(shipments.map((s) => s.carrier));
    return ["ALL", ...Array.from(set).sort()];
  }, [shipments]);

  const filtered = shipments.filter((s) => {
    if (!includeCancelled && s.status === "cancelled") return false;
    if (direction !== "ALL" && s.direction !== direction) return false;
    if (carrier !== "ALL" && s.carrier !== carrier) return false;
    if (mode !== "ALL" && s.mode !== mode) return false;
    if (status !== "ALL" && s.status !== status) return false;
    if (hazOnly && !s.hazmat) return false;
    if (q) {
      const ql = q.toLowerCase();
      const hay = [s.reference, s.shipment_id, s.commodity, s.destination.city, s.supplier, s.consignee, s.po_numbers, s.booking_number]
        .filter(Boolean).join(" ").toLowerCase();
      if (!hay.includes(ql)) return false;
    }
    return true;
  });

  const counts = {
    all: shipments.length,
    outbound: shipments.filter((s) => s.direction === "outbound").length,
    inbound: shipments.filter((s) => s.direction === "inbound").length,
    hazmat: shipments.filter((s) => s.hazmat).length,
    cancelled: shipments.filter((s) => s.status === "cancelled").length,
  };

  const quickStatus = async (s, next) => {
    try {
      await api.put(`/shipments/${s.shipment_id}`, { status: next });
      toast.success(`${s.shipment_id} → ${next}`);
      load();
    } catch (e) {
      toast.error("Failed to update status");
    }
  };

  const performCancel = async () => {
    if (!confirmCancel) return;
    try {
      await api.delete(`/shipments/${confirmCancel.shipment_id}`, { data: { reason: confirmCancel.reason || "Cancelled by dispatcher" } });
      toast.success(`${confirmCancel.shipment_id} cancelled`);
      setConfirmCancel(null);
      load();
    } catch (e) {
      toast.error("Failed to cancel");
    }
  };

  const composeRoutingGuide = async (s) => {
    try {
      const { data } = await api.post(`/shipments/${s.shipment_id}/email-routing-guide`);
      setEmailModal({ kind: "routing", shipment: s, data });
    } catch (e) { toast.error("Failed to compose"); }
  };
  const composeCarrierEmail = async (s, template = "request_eta") => {
    try {
      const { data } = await api.post(`/shipments/${s.shipment_id}/email-carrier`, { template });
      setEmailModal({ kind: "carrier", shipment: s, data, template });
    } catch (e) { toast.error("Failed to compose"); }
  };
  const downloadBOL = (s) => {
    if (!s.carrier_bol_file_id) { toast.error("No BOL on file"); return; }
    const a = document.createElement("a");
    a.href = `${BACKEND_URL}/api/shipments/${s.shipment_id}/bol-download`;
    a.download = s.carrier_bol_filename || `BOL_${s.shipment_id}.pdf`;
    document.body.appendChild(a); a.click(); a.remove();
  };
  const uploadBOL = async (file) => {
    if (!bolUpload || !file) return;
    try {
      const fd = new FormData(); fd.append("file", file);
      await api.post(`/shipments/${bolUpload.shipment_id}/bol-upload`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success(`BOL uploaded for ${bolUpload.shipment_id}`);
      setBolUpload(null); load();
    } catch (e) { toast.error("BOL upload failed"); }
  };
  const copyEmail = (txt) => { navigator.clipboard.writeText(txt); toast.success("Copied to clipboard"); };

  return (
    <>
      <Topbar title="Shipments" subtitle={`${filtered.length} of ${shipments.length} shipments · ${counts.outbound} outbound · ${counts.inbound} inbound · ${counts.hazmat} hazmat · ${counts.cancelled} cancelled`} />
      <div className="p-4 md:p-6 space-y-4">

        <Card className="hud-surface p-3" data-testid="direction-toggle">
          <div className="flex gap-2 flex-wrap">
            {[
              { id: "ALL", label: "All", count: counts.all },
              { id: "outbound", label: "Outbound", count: counts.outbound, Icon: ArrowUpFromLine },
              { id: "inbound", label: "Inbound", count: counts.inbound, Icon: ArrowDownToLine },
            ].map((d) => (
              <button
                key={d.id}
                onClick={() => setDirection(d.id)}
                data-testid={`direction-${d.id}`}
                className={`px-4 py-2 rounded-md text-xs font-mono uppercase tracking-wider transition-all border flex items-center gap-2 ${
                  direction === d.id ? "bg-cyan-500 text-black border-cyan-400 hud-glow-cyan" : "bg-white/[0.02] text-slate-300 border-white/5 hover:border-cyan-500/40"
                }`}
              >
                {d.Icon && <d.Icon size={13} />}
                {d.label} <span className="opacity-70">({d.count})</span>
              </button>
            ))}
            <button
              onClick={() => setIncludeCancelled(!includeCancelled)}
              data-testid="show-cancelled-toggle"
              className={`px-4 py-2 rounded-md text-xs font-mono uppercase tracking-wider transition-all border flex items-center gap-2 ${
                includeCancelled ? "bg-slate-200 text-black border-slate-300" : "bg-white/[0.02] text-slate-400 border-white/5 hover:border-slate-300/40"
              }`}
            >
              <XCircle size={13} /> Show Cancelled ({counts.cancelled})
            </button>
            <button
              onClick={() => setHazOnly(!hazOnly)}
              data-testid="hazmat-toggle"
              className={`ml-auto px-4 py-2 rounded-md text-xs font-mono uppercase tracking-wider transition-all border flex items-center gap-2 ${
                hazOnly ? "bg-red-500 text-black border-red-400 shadow-[0_0_18px_rgba(255,59,48,0.4)]" : "bg-white/[0.02] text-slate-300 border-white/5 hover:border-red-500/40"
              }`}
            >
              <AlertTriangle size={13} /> HAZMAT ONLY ({counts.hazmat})
            </button>
          </div>
        </Card>

        <Card className="hud-surface p-3" data-testid="carrier-toggle">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-2 px-1">Carrier Toggle</div>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {carriers.map((c) => (
              <button
                key={c}
                onClick={() => setCarrier(c)}
                data-testid={`carrier-pill-${c}`}
                className={`shrink-0 px-3 py-1.5 rounded-md text-xs font-mono uppercase tracking-wider transition-all border ${
                  carrier === c
                    ? "bg-cyan-500 text-black border-cyan-400 hud-glow-cyan"
                    : "bg-white/[0.02] text-slate-400 border-white/5 hover:border-cyan-500/40 hover:text-cyan-300"
                }`}
              >{c}</button>
            ))}
          </div>
        </Card>

        <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
          <div className="md:col-span-5 relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <Input
              data-testid="shipment-search"
              value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="Search ref, PO#, supplier, consignee, destination..."
              className="pl-9 bg-[#131821] border-white/10 text-white focus:border-cyan-500"
            />
          </div>
          <div className="md:col-span-3 flex gap-1 overflow-x-auto">
            {["ALL", ...MODE_OPTIONS].map((m) => (
              <button key={m} onClick={() => setMode(m)} className={`px-2.5 py-1.5 rounded text-[11px] font-mono uppercase border ${mode === m ? "bg-cyan-500/15 text-cyan-300 border-cyan-500/40" : "border-white/5 text-slate-400 hover:text-white"}`}>{m}</button>
            ))}
          </div>
          <div className="md:col-span-4 flex gap-1 overflow-x-auto">
            {["ALL", "in_transit", "delayed", "delivered", "pending", "cancelled"].map((st) => (
              <button key={st} onClick={() => setStatus(st)} className={`px-2.5 py-1.5 rounded text-[11px] font-mono uppercase border ${status === st ? "bg-cyan-500/15 text-cyan-300 border-cyan-500/40" : "border-white/5 text-slate-400 hover:text-white"}`}>{st}</button>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 px-1">
          <div className="text-[10px] font-mono text-slate-500">
            <ExternalLink size={10} className="inline mr-1 text-cyan-400" />
            Cyan-underlined fields deep-link to <span className="text-cyan-400">SAP S/4HANA</span>.{" "}
            <span className="text-cyan-300">Drag any column header by its grip handle to reposition</span> · drag the right edge to resize.
            {canEdit && <span className="ml-2 text-emerald-400">Edit / Cancel / Email / BOL actions on the right →</span>}
          </div>
          <button
            onClick={() => setColCustomizerOpen(true)}
            data-testid="customize-columns-btn"
            className="px-3 py-1.5 rounded text-xs font-mono uppercase tracking-wider border border-white/10 text-slate-300 hover:border-cyan-400/50 hover:text-cyan-300 flex items-center gap-1.5"
          >
            <Settings2 size={12} /> Columns ({visibleCols.length}/{cols.length})
          </button>
        </div>

        <Card className="hud-surface overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" style={{ tableLayout: "fixed", minWidth: visibleCols.reduce((a, c) => a + c.width, 0) + (canEdit ? 160 : 0) }}>
              <thead className="bg-[#0B0E14] text-[10px] font-mono text-cyan-400 uppercase tracking-wider sticky top-0">
                <tr>
                  {visibleCols.map((c) => {
                    const m = colMeta[c.id] || {};
                    const align = m.align === "right" ? "text-right" : m.align === "center" ? "text-center" : "text-left";
                    const isDragging = dragColId === c.id;
                    const isOver = overColId === c.id && dragColId && dragColId !== c.id;
                    return (
                      <th
                        key={c.id}
                        data-testid={`col-header-${c.id}`}
                        className={`py-3 px-3 ${align} relative group transition-colors ${isOver ? "bg-cyan-500/15" : ""} ${isDragging ? "opacity-50" : ""}`}
                        style={{ width: c.width }}
                        onDragOver={(e) => {
                          if (!dragColId) return;
                          e.preventDefault();
                          e.dataTransfer.dropEffect = "move";
                          if (overColId !== c.id) setOverColId(c.id);
                        }}
                        onDragLeave={() => { if (overColId === c.id) setOverColId(null); }}
                        onDrop={(e) => {
                          e.preventDefault();
                          const src = e.dataTransfer.getData("text/plain");
                          reorderCol(src, c.id);
                          setDragColId(null); setOverColId(null);
                        }}
                      >
                        <span
                          draggable
                          onDragStart={(e) => {
                            e.dataTransfer.setData("text/plain", c.id);
                            e.dataTransfer.effectAllowed = "move";
                            setDragColId(c.id);
                          }}
                          onDragEnd={() => { setDragColId(null); setOverColId(null); }}
                          data-testid={`col-drag-${c.id}`}
                          className="inline-flex items-center gap-1 cursor-grab active:cursor-grabbing select-none hover:text-cyan-300"
                          title="Drag to reorder column"
                        >
                          <GripVertical size={10} className="opacity-30 group-hover:opacity-70" />
                          {m.label}
                        </span>
                        <span
                          onMouseDown={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            const startX = e.clientX; const startW = c.width;
                            const onMove = (ev) => {
                              const w = Math.max(50, startW + (ev.clientX - startX));
                              setCols((arr) => arr.map((x) => x.id === c.id ? { ...x, width: w } : x));
                            };
                            const onUp = () => { document.removeEventListener("mousemove", onMove); document.removeEventListener("mouseup", onUp); };
                            document.addEventListener("mousemove", onMove);
                            document.addEventListener("mouseup", onUp);
                          }}
                          className="absolute right-0 top-0 h-full w-1 cursor-col-resize opacity-0 group-hover:opacity-100 bg-cyan-400/40 hover:bg-cyan-400"
                          data-testid={`col-resize-${c.id}`}
                        />
                      </th>
                    );
                  })}
                  {canEdit && <th className="py-3 px-3 text-center" style={{ width: 160 }}>Actions</th>}
                </tr>
              </thead>
              <tbody className="font-mono">
                {filtered.map((s) => (
                  <tr key={s.shipment_id} className={`border-t border-white/5 hover:bg-white/[0.02] ${s.status === "cancelled" ? "opacity-50" : ""}`} data-testid={`shipment-row-${s.shipment_id}`}>
                    {visibleCols.map((c) => <td key={c.id} className="py-2.5 px-3 truncate" style={{ width: c.width, maxWidth: c.width }}>{renderCell(c.id, s, colMeta, canEdit, quickStatus)}</td>)}
                    {canEdit && (
                      <td className="py-2.5 px-3 text-center">
                        <div className="inline-flex items-center gap-0.5 flex-wrap">
                          <button
                            data-testid={`edit-shipment-${s.shipment_id}`}
                            onClick={() => setEditing({ ...s })}
                            disabled={s.status === "cancelled"}
                            className="p-1.5 rounded text-cyan-300 hover:bg-cyan-500/10 disabled:opacity-30 disabled:cursor-not-allowed"
                            title="Edit shipment"
                          ><Pencil size={13} /></button>
                          <button
                            data-testid={`email-routing-${s.shipment_id}`}
                            onClick={() => composeRoutingGuide(s)}
                            className="p-1.5 rounded text-emerald-300 hover:bg-emerald-500/10"
                            title="Email routing guide to customer"
                          ><Mail size={13} /></button>
                          <button
                            data-testid={`email-carrier-${s.shipment_id}`}
                            onClick={() => composeCarrierEmail(s, "request_eta")}
                            className="p-1.5 rounded text-yellow-300 hover:bg-yellow-500/10"
                            title="Email carrier (ETA / POD / exception)"
                          ><Mail size={13} className="rotate-180" /></button>
                          <button
                            data-testid={`bol-action-${s.shipment_id}`}
                            onClick={() => s.carrier_bol_file_id ? downloadBOL(s) : setBolUpload(s)}
                            className={`p-1.5 rounded ${s.carrier_bol_file_id ? "text-emerald-300 hover:bg-emerald-500/10" : "text-slate-400 hover:bg-cyan-500/10"}`}
                            title={s.carrier_bol_file_id ? "Download stored BOL" : "Upload carrier BOL"}
                          >{s.carrier_bol_file_id ? <FileText size={13} /> : <Upload size={13} />}</button>
                          <button
                            data-testid={`cancel-shipment-${s.shipment_id}`}
                            onClick={() => setConfirmCancel({ shipment_id: s.shipment_id, reference: s.reference, reason: "" })}
                            disabled={s.status === "cancelled"}
                            className="p-1.5 rounded text-red-400 hover:bg-red-500/10 disabled:opacity-30 disabled:cursor-not-allowed"
                            title="Cancel shipment (soft delete)"
                          ><XCircle size={13} /></button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr><td colSpan={visibleCols.length + (canEdit ? 1 : 0)} className="text-center py-12 text-slate-500">No shipments match the current filters.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {/* Edit modal */}
      <EditShipmentDialog
        shipment={editing}
        onClose={() => setEditing(null)}
        onSaved={() => { setEditing(null); load(); }}
      />

      {/* Cancel confirmation */}
      <Dialog open={!!confirmCancel} onOpenChange={(o) => !o && setConfirmCancel(null)}>
        <DialogContent className="bg-[#131821] border border-red-500/30 text-white max-w-md" data-testid="cancel-shipment-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-red-400 flex items-center gap-2"><XCircle size={18} /> Cancel Shipment</DialogTitle>
          </DialogHeader>
          {confirmCancel && (
            <div className="space-y-3">
              <p className="text-sm text-slate-300">
                This will mark <span className="font-mono text-cyan-300">{confirmCancel.shipment_id}</span> ({confirmCancel.reference}) as <strong>cancelled</strong>.
                The record is preserved (soft delete) — you can re-enable it later from the database if needed.
              </p>
              <div>
                <label className="text-[10px] font-mono uppercase text-slate-500">Reason (optional)</label>
                <Input
                  value={confirmCancel.reason}
                  onChange={(e) => setConfirmCancel({ ...confirmCancel, reason: e.target.value })}
                  placeholder="e.g., Carrier no-show, customer pull"
                  className="mt-1 bg-[#0B0E14] border-white/10"
                  data-testid="cancel-reason-input"
                />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmCancel(null)} data-testid="cancel-dialog-close">Keep Shipment</Button>
            <Button onClick={performCancel} className="bg-red-500 hover:bg-red-600 text-white" data-testid="cancel-dialog-confirm">Confirm Cancel</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Column customizer */}
      <Dialog open={colCustomizerOpen} onOpenChange={setColCustomizerOpen}>
        <DialogContent className="bg-[#131821] border border-cyan-500/30 text-white max-w-lg" data-testid="column-customizer-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-cyan-300 flex items-center gap-2"><Settings2 size={16} /> Customize Columns</DialogTitle>
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500">Toggle visibility · drag grip to reorder · edit width</div>
          </DialogHeader>
          <div className="grid grid-cols-1 gap-2 max-h-[55vh] overflow-y-auto">
            {cols.map((c) => {
              const m = colMeta[c.id] || {};
              const isDragging = dragColId === c.id;
              const isOver = overColId === c.id && dragColId && dragColId !== c.id;
              return (
                <div
                  key={c.id}
                  data-testid={`col-row-${c.id}`}
                  onDragOver={(e) => { if (!dragColId) return; e.preventDefault(); if (overColId !== c.id) setOverColId(c.id); }}
                  onDragLeave={() => { if (overColId === c.id) setOverColId(null); }}
                  onDrop={(e) => {
                    e.preventDefault();
                    const src = e.dataTransfer.getData("text/plain");
                    reorderCol(src, c.id);
                    setDragColId(null); setOverColId(null);
                  }}
                  className={`flex items-center gap-2 p-2 rounded border ${isOver ? "border-cyan-400 bg-cyan-500/10" : "border-white/5"} ${isDragging ? "opacity-50" : ""} hover:border-cyan-500/30 transition-colors`}
                >
                  <span
                    draggable
                    onDragStart={(e) => { e.dataTransfer.setData("text/plain", c.id); e.dataTransfer.effectAllowed = "move"; setDragColId(c.id); }}
                    onDragEnd={() => { setDragColId(null); setOverColId(null); }}
                    data-testid={`col-row-drag-${c.id}`}
                    className="cursor-grab active:cursor-grabbing text-slate-500 hover:text-cyan-300 p-1"
                    title="Drag to reorder"
                  >
                    <GripVertical size={14} />
                  </span>
                  <label className="flex items-center gap-2 flex-1 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={c.visible}
                      onChange={() => setCols((arr) => arr.map((x) => x.id === c.id ? { ...x, visible: !x.visible } : x))}
                      className="accent-cyan-500"
                      data-testid={`col-toggle-${c.id}`}
                    />
                    <span className="text-sm text-slate-200 flex-1">{m.label}</span>
                  </label>
                  <input
                    type="number" min={50} max={400} value={c.width}
                    onChange={(e) => setCols((arr) => arr.map((x) => x.id === c.id ? { ...x, width: parseInt(e.target.value || 50) } : x))}
                    className="w-16 bg-[#0B0E14] border border-white/10 rounded px-2 py-0.5 text-xs font-mono"
                  />
                </div>
              );
            })}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCols(DEFAULT_COLUMNS.map((c) => ({ id: c.id, visible: c.default, width: c.width })))} data-testid="col-reset-btn">Reset Defaults</Button>
            <Button onClick={() => setColCustomizerOpen(false)} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold">Done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Email composer (routing guide or carrier) */}
      <Dialog open={!!emailModal} onOpenChange={(o) => !o && setEmailModal(null)}>
        <DialogContent className="bg-[#131821] border border-cyan-500/30 text-white max-w-2xl" data-testid="email-modal">
          <DialogHeader>
            <DialogTitle className="font-display text-cyan-300 flex items-center gap-2">
              <Mail size={16} /> {emailModal?.kind === "routing" ? "Routing Guide to Customer" : "Email Carrier"} · {emailModal?.shipment?.shipment_id}
            </DialogTitle>
          </DialogHeader>
          {emailModal && (
            <div className="space-y-3">
              {emailModal.kind === "carrier" && (
                <div className="flex flex-wrap gap-2">
                  {["request_eta", "request_pod", "exception_inquiry", "rate_confirmation"].map((t) => (
                    <button key={t} onClick={() => composeCarrierEmail(emailModal.shipment, t)} data-testid={`tpl-${t}`}
                      className={`px-3 py-1.5 rounded text-xs font-mono uppercase border ${emailModal.template === t ? "bg-cyan-500 text-black border-cyan-400" : "border-white/10 text-slate-300 hover:border-cyan-400/40"}`}>
                      {t.replace("_", " ")}
                    </button>
                  ))}
                </div>
              )}
              <div>
                <label className="text-[10px] font-mono uppercase text-cyan-400">To</label>
                <Input readOnly value={emailModal.data.to || "(no email on file — fill in customer/carrier contact email on shipment)"} className="mt-1 bg-[#0B0E14] border-white/10" />
              </div>
              <div>
                <label className="text-[10px] font-mono uppercase text-cyan-400">Subject</label>
                <Input readOnly value={emailModal.data.subject} className="mt-1 bg-[#0B0E14] border-white/10 font-mono text-xs" />
              </div>
              <div>
                <label className="text-[10px] font-mono uppercase text-cyan-400">Body</label>
                <textarea readOnly value={emailModal.data.body} rows={14} className="w-full mt-1 bg-[#0B0E14] border border-white/10 rounded px-3 py-2 text-xs font-mono whitespace-pre-wrap" data-testid="email-body" />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => copyEmail(emailModal?.data?.body || "")} data-testid="email-copy-btn">Copy Body</Button>
            <a
              href={emailModal?.data?.mailto || "#"}
              data-testid="email-mailto"
              className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded bg-cyan-500 hover:bg-cyan-400 text-black font-bold text-sm"
            ><Mail size={14} /> Open in Mail Client</a>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* BOL upload */}
      <Dialog open={!!bolUpload} onOpenChange={(o) => !o && setBolUpload(null)}>
        <DialogContent className="bg-[#131821] border border-cyan-500/30 text-white max-w-md" data-testid="bol-upload-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-cyan-300 flex items-center gap-2"><Upload size={16} /> Upload Carrier BOL · {bolUpload?.shipment_id}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <p className="text-sm text-slate-300">Upload the signed BOL (PDF preferred). Drivers/carriers in the portal can also upload here.</p>
            <input type="file" accept="application/pdf,image/*"
              onChange={(e) => uploadBOL(e.target.files?.[0])}
              data-testid="bol-file-input"
              className="block w-full text-sm text-slate-300 file:mr-3 file:py-2 file:px-3 file:rounded file:border-0 file:bg-cyan-500 file:text-black file:font-bold file:cursor-pointer" />
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

// Cell renderer for column-customized table
function renderCell(colId, s, _meta, canEdit, quickStatus) {
  switch (colId) {
    case "done":
      return s.done ? <CheckCircle2 size={14} className="text-emerald-400 inline" /> : <div className="w-3.5 h-3.5 rounded-sm border border-slate-600 inline-block" />;
    case "ship_date":
      return <span className="text-slate-300 text-xs whitespace-nowrap">{s.ship_date || s.pickup_date}</span>;
    case "ship_day":
      return <span className="text-cyan-300 text-xs">{s.ship_day || "—"}</span>;
    case "supplier_origin":
      return s.direction === "inbound" && s.supplier
        ? <SapLink path="supplier" params={{ name: s.supplier }} title={`Open ${s.supplier} in SAP`} testid={`sap-supplier-${s.shipment_id}`}>{s.supplier}</SapLink>
        : <span className="truncate" title={s.origin?.name}>{s.origin?.city}</span>;
    case "consignee_dest":
      return s.consignee
        ? <SapLink path="consignee" params={{ name: s.consignee }} testid={`sap-consignee-${s.shipment_id}`}>{s.consignee}</SapLink>
        : <span className="truncate">{s.destination?.city}</span>;
    case "carrier":
      return <span className="text-slate-300 truncate">{s.carrier}</span>;
    case "po":
      return s.po_numbers
        ? <SapLink path="po" params={{ po: s.po_numbers }} testid={`sap-po-${s.shipment_id}`}>{s.po_numbers}</SapLink>
        : <SapLink path="so" params={{ ref: s.reference }} testid={`sap-so-${s.shipment_id}`}>{s.reference}</SapLink>;
    case "sap_delivery":
      return s.sap_delivery_no ? <SapLink path="delivery" params={{ id: s.sap_delivery_no }} testid={`sap-del-${s.shipment_id}`}>{s.sap_delivery_no}</SapLink> : <span className="text-slate-600">—</span>;
    case "skids":
      return <span className="text-right block text-slate-300">{s.pallet_count || s.skids || s.pieces}</span>;
    case "lbs":
      return <span className="text-right block text-slate-300">{Number(s.weight_lbs || 0).toLocaleString()}</span>;
    case "dimensions":
      return (s.length_in || s.width_in || s.height_in)
        ? <span className="text-slate-300 text-xs">{Math.round(s.length_in||0)}×{Math.round(s.width_in||0)}×{Math.round(s.height_in||0)}<span className="text-slate-500"> in</span></span>
        : <span className="text-slate-600">—</span>;
    case "nmfc":
      return s.nmfc_code || s.freight_class
        ? <span className="text-xs"><span className="text-cyan-300 font-mono">{s.nmfc_code || "—"}</span> {s.freight_class && <span className="text-slate-400">· cls {s.freight_class}</span>}</span>
        : <span className="text-slate-600">—</span>;
    case "accessorials":
      return (s.accessorials && s.accessorials.length)
        ? <span className="text-yellow-300 text-[10px] uppercase truncate">{s.accessorials.join(", ")}</span>
        : <span className="text-slate-600">—</span>;
    case "material_controller":
      return s.material_controller
        ? <SapLink path="user" params={{ name: s.material_controller }} testid={`sap-mc-${s.shipment_id}`}>{s.material_controller}</SapLink>
        : <span className="text-slate-500">—</span>;
    case "booking":
      return s.booking_number
        ? <SapLink path="booking" params={{ id: s.booking_number }} testid={`sap-booking-${s.shipment_id}`}>{s.booking_number}</SapLink>
        : <span className="text-slate-500">—</span>;
    case "bid_cost":
      return (
        <div className="text-right">
          {s.bid_cost ? <span className="text-emerald-400">${s.bid_cost.toLocaleString()}</span> : <span className="text-slate-500">—</span>}
          {s.fsc_pct ? <div className="text-[9px] text-yellow-400">+{s.fsc_pct}% FSC</div> : null}
        </div>
      );
    case "hz":
      return s.hazmat
        ? <span title={s.hazmat_class || "Hazmat"} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-red-500/15 text-red-300 border border-red-500/30 font-mono text-[9px]"><AlertTriangle size={9} /> HAZ</span>
        : <span className="text-slate-600">—</span>;
    case "status":
      if (canEdit && s.status !== "cancelled") {
        return (
          <select
            value={s.status}
            onChange={(e) => quickStatus(s, e.target.value)}
            data-testid={`status-select-${s.shipment_id}`}
            className={`bg-transparent border rounded px-2 py-0.5 font-mono text-[10px] uppercase cursor-pointer ${STATUS_BADGE[s.status] || "border-white/10 text-slate-400"}`}
          >
            {STATUS_OPTIONS.map((st) => <option key={st} value={st} className="bg-[#0B0E14]">{st}</option>)}
          </select>
        );
      }
      return <Badge className={`${STATUS_BADGE[s.status] || ""} font-mono text-[10px] uppercase`}>{s.status}</Badge>;
    default:
      return null;
  }
}

// -------------------- Edit Dialog --------------------
function EditShipmentDialog({ shipment, onClose, onSaved }) {
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (shipment) {
      setForm({
        reference: shipment.reference || "",
        mode: shipment.mode || "TL",
        carrier: shipment.carrier || "",
        status: shipment.status || "pending",
        direction: shipment.direction || "outbound",
        eta: shipment.eta?.slice(0, 10) || "",
        pickup_date: shipment.pickup_date || "",
        ship_date: shipment.ship_date || "",
        ship_day: shipment.ship_day || "",
        weight_lbs: shipment.weight_lbs ?? "",
        pieces: shipment.pieces ?? "",
        skids: shipment.skids ?? "",
        commodity: shipment.commodity || "",
        value_usd: shipment.value_usd ?? "",
        container_no: shipment.container_no || "",
        bol_no: shipment.bol_no || "",
        pro_no: shipment.pro_no || "",
        hazmat: !!shipment.hazmat,
        hazmat_class: shipment.hazmat_class || "",
        supplier: shipment.supplier || "",
        consignee: shipment.consignee || "",
        material_controller: shipment.material_controller || "",
        po_numbers: shipment.po_numbers || "",
        booking_number: shipment.booking_number || "",
        bid_cost: shipment.bid_cost ?? "",
        fsc_pct: shipment.fsc_pct ?? "",
        extras: shipment.extras || "",
        done: !!shipment.done,
        shipping_hours: shipment.shipping_hours || "",
        pickup_no: shipment.pickup_no || "",
        progress: shipment.progress ?? 0,
        origin_facility: shipment.origin?.facility || "",
        origin_city: shipment.origin?.city || "",
        destination_city: shipment.destination?.city || "",
        destination_lat: shipment.destination?.lat ?? "",
        destination_lng: shipment.destination?.lng ?? "",
      });
    }
  }, [shipment]);

  if (!shipment) return null;

  const set = (k) => (e) => {
    const v = e.target?.type === "checkbox" ? e.target.checked : (e.target?.value ?? e);
    setForm((f) => ({ ...f, [k]: v }));
  };

  const submit = async () => {
    setSaving(true);
    try {
      // Coerce numeric fields
      const payload = { ...form };
      ["weight_lbs", "pieces", "skids", "value_usd", "bid_cost", "fsc_pct", "progress", "destination_lat", "destination_lng"].forEach((k) => {
        if (payload[k] === "" || payload[k] == null) delete payload[k];
        else payload[k] = Number(payload[k]);
      });
      // Drop empty strings to keep server stable
      Object.keys(payload).forEach((k) => { if (payload[k] === "") delete payload[k]; });
      await api.put(`/shipments/${shipment.shipment_id}`, payload);
      toast.success(`${shipment.shipment_id} updated`);
      onSaved?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to update");
    } finally {
      setSaving(false);
    }
  };

  const Field = ({ label, children }) => (
    <div className="space-y-1">
      <label className="text-[10px] font-mono uppercase tracking-wider text-cyan-400">{label}</label>
      {children}
    </div>
  );
  const inputCls = "w-full bg-[#0B0E14] border border-white/10 rounded px-3 py-2 text-sm text-white focus:border-cyan-500 focus:outline-none font-mono";

  return (
    <Dialog open={!!shipment} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="bg-[#131821] border border-cyan-500/30 text-white max-w-5xl max-h-[90vh] overflow-y-auto" data-testid="edit-shipment-dialog">
        <DialogHeader>
          <DialogTitle className="font-display text-cyan-300 flex items-center gap-2">
            <Pencil size={18} /> Edit Shipment <span className="font-mono text-xs text-slate-400 ml-2">{shipment.shipment_id}</span>
          </DialogTitle>
          <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500">All fields editable · Saves to MongoDB on confirm</div>
        </DialogHeader>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 py-2">
          <Field label="Reference"><input className={inputCls} value={form.reference || ""} onChange={set("reference")} data-testid="edit-reference" /></Field>
          <Field label="Mode">
            <select className={inputCls} value={form.mode || "TL"} onChange={set("mode")} data-testid="edit-mode">
              {MODE_OPTIONS.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </Field>
          <Field label="Carrier"><input className={inputCls} value={form.carrier || ""} onChange={set("carrier")} data-testid="edit-carrier" /></Field>

          <Field label="Status">
            <select className={inputCls} value={form.status || "pending"} onChange={set("status")} data-testid="edit-status">
              {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="Direction">
            <select className={inputCls} value={form.direction || "outbound"} onChange={set("direction")} data-testid="edit-direction">
              {DIRECTION_OPTIONS.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </Field>
          <Field label="Progress (0-1)"><input type="number" step="0.05" min="0" max="1" className={inputCls} value={form.progress ?? 0} onChange={set("progress")} /></Field>

          <Field label="Pickup Date"><input type="date" className={inputCls} value={form.pickup_date || ""} onChange={set("pickup_date")} data-testid="edit-pickup-date" /></Field>
          <Field label="Ship Date"><input type="date" className={inputCls} value={form.ship_date || ""} onChange={set("ship_date")} /></Field>
          <Field label="Ship Day">
            <select className={inputCls} value={form.ship_day || ""} onChange={set("ship_day")}>
              <option value="">—</option>
              {["MON", "TUE", "WED", "THR", "FRI", "SAT", "SUN"].map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </Field>

          <Field label="ETA"><input type="date" className={inputCls} value={form.eta || ""} onChange={set("eta")} /></Field>
          <Field label="Shipping Hours"><input className={inputCls} value={form.shipping_hours || ""} onChange={set("shipping_hours")} placeholder="0700-1500" /></Field>
          <Field label="Pickup #"><input className={inputCls} value={form.pickup_no || ""} onChange={set("pickup_no")} /></Field>

          <Field label="Weight (lbs)"><input type="number" className={inputCls} value={form.weight_lbs ?? ""} onChange={set("weight_lbs")} data-testid="edit-weight" /></Field>
          <Field label="Skids"><input type="number" className={inputCls} value={form.skids ?? ""} onChange={set("skids")} /></Field>
          <Field label="Pieces"><input type="number" className={inputCls} value={form.pieces ?? ""} onChange={set("pieces")} /></Field>

          <Field label="Commodity"><input className={inputCls} value={form.commodity || ""} onChange={set("commodity")} data-testid="edit-commodity" /></Field>
          <Field label="Value (USD)"><input type="number" className={inputCls} value={form.value_usd ?? ""} onChange={set("value_usd")} /></Field>
          <Field label="Bid Cost"><input type="number" className={inputCls} value={form.bid_cost ?? ""} onChange={set("bid_cost")} /></Field>

          <Field label="FSC %"><input type="number" step="0.1" className={inputCls} value={form.fsc_pct ?? ""} onChange={set("fsc_pct")} /></Field>
          <Field label="Extras"><input className={inputCls} value={form.extras || ""} onChange={set("extras")} /></Field>
          <Field label="Material Controller"><input className={inputCls} value={form.material_controller || ""} onChange={set("material_controller")} /></Field>

          <Field label="Container #"><input className={inputCls} value={form.container_no || ""} onChange={set("container_no")} /></Field>
          <Field label="BOL #"><input className={inputCls} value={form.bol_no || ""} onChange={set("bol_no")} /></Field>
          <Field label="PRO #"><input className={inputCls} value={form.pro_no || ""} onChange={set("pro_no")} /></Field>

          <Field label="Booking #"><input className={inputCls} value={form.booking_number || ""} onChange={set("booking_number")} /></Field>
          <Field label="PO Numbers"><input className={inputCls} value={form.po_numbers || ""} onChange={set("po_numbers")} /></Field>
          <Field label="Supplier"><input className={inputCls} value={form.supplier || ""} onChange={set("supplier")} /></Field>

          <Field label="Consignee"><input className={inputCls} value={form.consignee || ""} onChange={set("consignee")} /></Field>
          <Field label="Origin Facility">
            <select className={inputCls} value={form.origin_facility || ""} onChange={set("origin_facility")}>
              {FACILITY_OPTIONS.map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}
            </select>
          </Field>
          <Field label="Origin City"><input className={inputCls} value={form.origin_city || ""} onChange={set("origin_city")} /></Field>

          <Field label="Destination City"><input className={inputCls} value={form.destination_city || ""} onChange={set("destination_city")} /></Field>
          <Field label="Destination Lat"><input type="number" step="0.0001" className={inputCls} value={form.destination_lat ?? ""} onChange={set("destination_lat")} /></Field>
          <Field label="Destination Lng"><input type="number" step="0.0001" className={inputCls} value={form.destination_lng ?? ""} onChange={set("destination_lng")} /></Field>

          <div className="md:col-span-3 grid grid-cols-2 md:grid-cols-4 gap-4 pt-2 border-t border-white/5">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={!!form.hazmat} onChange={set("hazmat")} className="accent-red-500" data-testid="edit-hazmat" />
              <span className="font-mono text-[11px] uppercase text-red-300">Hazmat</span>
            </label>
            <Field label="Hazmat Class"><input className={inputCls} value={form.hazmat_class || ""} onChange={set("hazmat_class")} placeholder="Class 9 (Li-ion)" disabled={!form.hazmat} /></Field>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={!!form.done} onChange={set("done")} className="accent-emerald-500" />
              <span className="font-mono text-[11px] uppercase text-emerald-300">Marked Done</span>
            </label>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} data-testid="edit-cancel-btn">Cancel</Button>
          <Button onClick={submit} disabled={saving} className="bg-cyan-500 hover:bg-cyan-600 text-black font-bold" data-testid="edit-save-btn">
            {saving ? "Saving..." : "Save Changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
